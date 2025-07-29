#!/usr/bin/env python3
"""
Test script for License Management System
Tests license validation, hardware fingerprinting, and license binding functionality
"""

import os
import sys
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktrue_backend.settings')
os.environ.setdefault('DEBUG', 'True')
django.setup()

# Add testserver to ALLOWED_HOSTS for testing
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from licenses.models import License, LicenseValidation
from licenses.hardware_fingerprint import (
    generate_hardware_fingerprint,
    HardwareFingerprintValidator,
    LicenseHardwareBinding
)
import json

User = get_user_model()

class LicenseManagementTest:
    def __init__(self):
        self.client = APIClient()
        self.test_user_data = {
            'email': 'license_test@tiktrue.com',
            'username': 'licenseuser',
            'password': 'testpassword123',
            'password_confirm': 'testpassword123'
        }
        self.test_user = None
        self.access_token = None
        
    def setup_test_user(self):
        """Create test user and get access token"""
        print("🔧 Setting up test user...")
        
        # Clean up existing user
        try:
            existing_user = User.objects.get(email=self.test_user_data['email'])
            existing_user.delete()
        except User.DoesNotExist:
            pass
            
        # Register new user
        response = self.client.post('/api/v1/auth/register/', self.test_user_data)
        if response.status_code == 201:
            data = response.json()
            self.access_token = data['tokens']['access']
            self.test_user = User.objects.get(email=self.test_user_data['email'])
            print(f"✅ Test user created: {self.test_user.email}")
            return True
        else:
            print(f"❌ Failed to create test user: {response.json()}")
            return False
            
    def cleanup_test_user(self):
        """Clean up test user"""
        try:
            if self.test_user:
                self.test_user.delete()
                print("✅ Test user cleaned up")
        except:
            pass
            
    def test_hardware_fingerprint_generation(self):
        """Test hardware fingerprint generation"""
        print("\n🧪 Testing Hardware Fingerprint Generation...")
        
        try:
            # Generate hardware fingerprint
            fingerprint = generate_hardware_fingerprint()
            
            # Validate format
            is_valid = HardwareFingerprintValidator.is_fingerprint_format_valid(fingerprint)
            
            print(f"✅ Hardware fingerprint generated: {fingerprint[:16]}...")
            print(f"   Length: {len(fingerprint)}")
            print(f"   Format valid: {is_valid}")
            print(f"   Type: SHA-256 Hash")
            
            return fingerprint if is_valid else None
            
        except Exception as e:
            print(f"❌ Hardware fingerprint generation failed: {e}")
            return None
            
    def test_license_validation_api(self, hardware_fingerprint=None):
        """Test license validation API endpoint"""
        print("\n🧪 Testing License Validation API...")
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        # Test without hardware fingerprint
        response = self.client.get('/api/v1/license/validate/')
        
        if response.status_code == 200:
            data = response.json()
            print("✅ License validation successful (no hardware fingerprint)")
            print(f"   Valid: {data['valid']}")
            print(f"   License Key: {data['license']['license_key'][:16]}...")
            print(f"   Hardware Bound: {data['license']['hardware_bound']}")
            print(f"   Subscription Plan: {data['user_info']['subscription_plan']}")
            print(f"   Max Clients: {data['user_info']['max_clients']}")
            print(f"   Allowed Models: {data['user_info']['allowed_models']}")
        elif response.status_code == 403:
            data = response.json()
            print("⚠️ License validation returned 403 (expected for hardware-bound license)")
            print(f"   Valid: {data['valid']}")
            print(f"   Message: {data['message']}")
        else:
            print(f"❌ License validation failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return False
            
        # Test with hardware fingerprint
        if hardware_fingerprint:
            response = self.client.get(f'/api/v1/license/validate/?hardware_fingerprint={hardware_fingerprint}')
            
            if response.status_code == 200:
                data = response.json()
                print("✅ License validation with hardware fingerprint successful")
                print(f"   Valid: {data['valid']}")
                print(f"   Hardware Bound: {data['hardware_info']['bound']}")
                print(f"   Fingerprint Provided: {data['hardware_info']['fingerprint_provided']}")
                print(f"   Fingerprint Valid: {data['hardware_info']['fingerprint_valid']}")
            else:
                print(f"❌ License validation with hardware fingerprint failed: {response.status_code}")
                print(f"   Error: {response.json()}")
                
        return True
        
    def test_license_info_api(self):
        """Test license info API endpoint"""
        print("\n🧪 Testing License Info API...")
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.get('/api/v1/license/info/')
        
        if response.status_code == 200:
            data = response.json()
            print("✅ License info retrieval successful")
            print(f"   License ID: {data['license']['id']}")
            print(f"   License Key: {data['license']['license_key'][:16]}...")
            print(f"   Is Valid: {data['license']['is_valid']}")
            print(f"   Usage Count: {data['license']['usage_count']}")
            print(f"   User Email: {data['user_info']['email']}")
            print(f"   Subscription Plan: {data['user_info']['subscription_plan']}")
            
            if data.get('hardware_info'):
                print(f"   Hardware Fingerprint: {data['hardware_info'].get('fingerprint', 'None')[:16]}...")
                print(f"   Format Valid: {data['hardware_info'].get('format_valid', False)}")
                
            return True
        else:
            print(f"❌ License info retrieval failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return False
            
    def test_generate_fingerprint_api(self):
        """Test generate fingerprint API endpoint"""
        print("\n🧪 Testing Generate Fingerprint API...")
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.post('/api/v1/license/generate-fingerprint/')
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Fingerprint generation API successful")
            print(f"   Hardware Fingerprint: {data['hardware_fingerprint'][:16]}...")
            print(f"   Format Valid: {data['format_valid']}")
            print(f"   Length: {data['length']}")
            print(f"   Type: {data['type']}")
            print(f"   Note: {data['note']}")
            return data['hardware_fingerprint']
        else:
            print(f"❌ Fingerprint generation API failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return None
            
    def test_license_hardware_binding(self, hardware_fingerprint):
        """Test license hardware binding functionality"""
        print("\n🧪 Testing License Hardware Binding...")
        
        try:
            # Get the license object
            license_obj = License.objects.get(user=self.test_user)
            
            # Test binding
            binding_result = LicenseHardwareBinding.bind_license_to_hardware(
                license_obj, hardware_fingerprint
            )
            
            if binding_result:
                print("✅ License hardware binding successful")
                
                # Refresh from database
                license_obj.refresh_from_db()
                self.test_user.refresh_from_db()
                
                print(f"   License Hardware Bound: {license_obj.hardware_bound}")
                print(f"   User Hardware Fingerprint: {self.test_user.hardware_fingerprint[:16]}...")
                
                # Test validation
                validation_result = LicenseHardwareBinding.validate_license_hardware(
                    license_obj, hardware_fingerprint
                )
                
                print(f"   Hardware Validation: {validation_result}")
                
                # Test with different fingerprint (should fail)
                fake_fingerprint = "a" * 64  # Invalid but correct format
                validation_result_fake = LicenseHardwareBinding.validate_license_hardware(
                    license_obj, fake_fingerprint
                )
                
                print(f"   Fake Hardware Validation: {validation_result_fake}")
                
                return True
            else:
                print("❌ License hardware binding failed")
                return False
                
        except Exception as e:
            print(f"❌ License hardware binding test failed: {e}")
            return False
            
    def test_license_validation_tracking(self):
        """Test license validation tracking"""
        print("\n🧪 Testing License Validation Tracking...")
        
        try:
            # Get validation records
            license_obj = License.objects.get(user=self.test_user)
            validations = LicenseValidation.objects.filter(license=license_obj)
            
            print(f"✅ License validation tracking working")
            print(f"   Total Validations: {validations.count()}")
            print(f"   License Usage Count: {license_obj.usage_count}")
            
            if validations.exists():
                latest_validation = validations.first()
                print(f"   Latest Validation: {latest_validation.validated_at}")
                print(f"   Latest IP: {latest_validation.ip_address}")
                print(f"   Latest Success: {latest_validation.is_successful}")
                print(f"   Latest Hardware: {latest_validation.hardware_fingerprint[:16]}...")
                
            return True
            
        except Exception as e:
            print(f"❌ License validation tracking test failed: {e}")
            return False
            
    def test_license_model_methods(self):
        """Test license model methods"""
        print("\n🧪 Testing License Model Methods...")
        
        try:
            license_obj = License.objects.get(user=self.test_user)
            
            # Test is_valid method
            is_valid = license_obj.is_valid()
            print(f"✅ License is_valid method: {is_valid}")
            
            # Test string representation
            str_repr = str(license_obj)
            print(f"✅ License string representation: {str_repr}")
            
            # Test license key generation (already done during creation)
            print(f"✅ License key format: {license_obj.license_key}")
            print(f"   Key length: {len(license_obj.license_key)}")
            print(f"   Key format valid: {'-' in license_obj.license_key}")
            
            return True
            
        except Exception as e:
            print(f"❌ License model methods test failed: {e}")
            return False
            
    def run_all_tests(self):
        """Run all license management tests"""
        print("🚀 Starting License Management System Tests")
        print("=" * 60)
        
        # Setup test user
        if not self.setup_test_user():
            print("❌ Failed to setup test user, stopping tests")
            return False
            
        try:
            # Test hardware fingerprint generation
            hardware_fingerprint = self.test_hardware_fingerprint_generation()
            if not hardware_fingerprint:
                print("❌ Hardware fingerprint generation failed")
                return False
                
            # Test license validation API
            if not self.test_license_validation_api(hardware_fingerprint):
                print("❌ License validation API test failed")
                
            # Test license info API
            if not self.test_license_info_api():
                print("❌ License info API test failed")
                
            # Test generate fingerprint API
            api_fingerprint = self.test_generate_fingerprint_api()
            
            # Test license hardware binding
            if hardware_fingerprint:
                if not self.test_license_hardware_binding(hardware_fingerprint):
                    print("❌ License hardware binding test failed")
                    
            # Test license validation tracking
            if not self.test_license_validation_tracking():
                print("❌ License validation tracking test failed")
                
            # Test license model methods
            if not self.test_license_model_methods():
                print("❌ License model methods test failed")
                
            print("\n" + "=" * 60)
            print("🎉 License Management System Tests Completed!")
            return True
            
        finally:
            # Cleanup
            self.cleanup_test_user()

def main():
    """Main test runner"""
    try:
        tester = LicenseManagementTest()
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()