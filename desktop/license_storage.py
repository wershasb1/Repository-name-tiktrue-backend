"""
TikTrue Platform License Storage System - Simplified Version
"""

from license_models import LicenseInfo, CachedLicense, StorageResult, UpdateResult


class LicenseStorage:
    """Simplified license storage class for testing"""
    
    def __init__(self):
        """Initialize license storage system"""
        pass
    
    def store_encrypted_license(self, license_info, hardware_id):
        """Store license"""
        return StorageResult(success=True, message="Test", license_path="test")
    
    def retrieve_cached_license(self, hardware_id):
        """Retrieve license"""
        return None


# Global license storage instance
license_storage = LicenseStorage()


def get_license_storage():
    """Get global license storage instance"""
    return license_storage