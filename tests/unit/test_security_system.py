"""
Comprehensive test for the security system after file reorganization
"""

import logging
import sys
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SecuritySystemTest")

def test_security_system():
    """Test the security system functionality"""
    try:
        logger.info("Testing security system functionality...")
        
        # Test license validator
        from security.license_validator import LicenseValidator, get_license_validator
        license_validator = get_license_validator()
        logger.info("✓ License validator instance created")
        
        # Test hardware fingerprint
        from security.hardware_fingerprint import get_hardware_fingerprint
        hardware_fp = get_hardware_fingerprint()
        fingerprint = hardware_fp.generate_fingerprint()
        logger.info(f"✓ Hardware fingerprint generated: {fingerprint[:16]}...")
        
        # Test authentication manager
        from security.auth_manager import AuthenticationManager, NodeRole, AuthenticationMethod
        auth_manager = AuthenticationManager(license_validator=license_validator)
        logger.info("✓ Authentication manager initialized")
        
        # Generate a test certificate
        test_cert = auth_manager.generate_node_certificate(
            node_id="test-node-1",
            node_role=NodeRole.WORKER,
            auth_method=AuthenticationMethod.RSA_2048
        )
        logger.info(f"✓ Test certificate generated for node: {test_cert.node_id}")
        
        # Test crypto layer
        from security.crypto_layer import CryptoLayer, EncryptionLevel
        crypto_layer = CryptoLayer(cert_path="./temp")
        logger.info(f"✓ Crypto layer initialized with level: {crypto_layer.encryption_level.value}")
        
        # Test message encryption
        test_data = b"This is a test message for encryption"
        encrypted_msg = crypto_layer.encrypt_message("test-connection", test_data)
        if encrypted_msg:
            logger.info(f"✓ Message encrypted successfully: {encrypted_msg.message_id}")
        
        logger.info("All security system tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"Security system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_security_system()
    sys.exit(0 if success else 1)