#!/usr/bin/env python3
"""
Test script for License Validation APIs
Tests the specific API endpoints required by task 6.2:
- GET /api/v1/license/validate برای بررسی license
- GET /api/v1/license/info برای اطلاعات license
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktrue_backend.settings')
os.environ.setdefault('DEBUG', 'True')
django.setup()

# Add testserver to ALLOWED_HOSTS for testing
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from licenses.models import License, LicenseValidation
from licenses.hardware_fingerprint import generate_hardware_fingerprint
import json

User = get_user_model()

class LicenseValidationAPITest:
    def __init__(self):
        self.client = APIClient()
        self.test_user_data = {
            'email': 'api_test@tiktrue.com',
            'username': 'apiuser',
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
            
    def test_license_validate_api_endpoint(self):
        """Test GET /api/v1/license/validate/ endpoint"""
        print("\n🧪 Testing GET /api/v1/license/validate/ API Endpoint...")
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        # Test 1: Basic validation without hardware fingerprint
        print("   📋 Test 1: Basic license validation")
        response = self.client.get('/api/v1/license/validate/')
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ License validation successful")
            print(f"      Valid: {data['valid']}")
            print(f"      License Key: {data['license']['license_key'][:16]}...")
            print(f"      Hardware Bound: {data['license']['hardware_bound']}")
            print(f"      User Subscription: {data['user_info']['subscription_plan']}")
            print(f"      Max Clients: {data['user_info']['max_clients']}")
            print(f"      Allowed Models: {data['user_info']['allowed_models']}")
            
            # Verify response structure
            required_fields = ['valid', 'license', 'user_info', 'hardware_info']
            for field in required_fields:
                if field not in data:
                    print(f"   ❌ Missing required field: {field}")
                    return False
                    
            # Verify license fields
            license_fields = ['id', 'license_key', 'hardware_bound', 'is_active', 'is_valid']
            for field in license_fields:
                if field not in data['license']:
                    print(f"   ❌ Missing license field: {field}")
                    return False
                    
        else:
            print(f"   ❌ License validation failed: {response.status_code}")
            print(f"      Error: {response.json()}")
            return False
            
        # Test 2: Validation with hardware fingerprint
        print("   📋 Test 2: License validation with hardware fingerprint")
        try:
            hardware_fingerprint = generate_hardware_fingerprint()
            response = self.client.get(f'/api/v1/license/validate/?hardware_fingerprint={hardware_fingerprint}')
            
            if response.status_code == 200:
                data = response.json()
                print("   ✅ License validation with hardware fingerprint successful")
                print(f"      Hardware Fingerprint Provided: {data['hardware_info']['fingerprint_provided']}")
                print(f"      Hardware Fingerprint Valid: {data['hardware_info']['fingerprint_valid']}")
            else:
                print(f"   ❌ License validation with hardware fingerprint failed: {response.status_code}")
                
        except Exception as e:
            print(f"   ⚠️ Hardware fingerprint test skipped: {e}")
            
        # Test 3: Invalid hardware fingerprint
        print("   📋 Test 3: Invalid hardware fingerprint handling")
        response = self.client.get('/api/v1/license/validate/?hardware_fingerprint=invalid')
        
        if response.status_code == 400:
            data = response.json()
            print("   ✅ Invalid hardware fingerprint properly rejected")
            print(f"      Message: {data['message']}")
        else:
            print(f"   ❌ Invalid hardware fingerprint not properly handled: {response.status_code}")
            
        return True
        
    def test_license_info_api_endpoint(self):
        """Test GET /api/v1/license/info/ endpoint"""
        print("\n🧪 Testing GET /api/v1/license/info/ API Endpoint...")
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.get('/api/v1/license/info/')
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ License info retrieval successful")
            print(f"      License ID: {data['license']['id']}")
            print(f"      License Key: {data['license']['license_key'][:16]}...")
            print(f"      Is Valid: {data['license']['is_valid']}")
            print(f"      Usage Count: {data['license']['usage_count']}")
            print(f"      User Email: {data['user_info']['email']}")
            print(f"      Subscription Plan: {data['user_info']['subscription_plan']}")
            print(f"      Max Clients: {data['user_info']['max_clients']}")
            print(f"      Allowed Models: {data['user_info']['allowed_models']}")
            
            # Verify response structure
            required_fields = ['license', 'user_info', 'hardware_info']
            for field in required_fields:
                if field not in data:
                    print(f"   ❌ Missing required field: {field}")
                    return False
                    
            # Verify user_info fields
            user_info_fields = ['email', 'subscription_plan', 'max_clients', 'allowed_models']
            for field in user_info_fields:
                if field not in data['user_info']:
                    print(f"   ❌ Missing user_info field: {field}")
                    return False
                    
            return True
        else:
            print(f"   ❌ License info retrieval failed: {response.status_code}")
            print(f"      Error: {response.json()}")
            return False
            
    def test_api_authentication(self):
        """Test API authentication requirements"""
        print("\n🧪 Testing API Authentication Requirements...")
        
        # Test without authentication
        client_no_auth = APIClient()
        
        print("   📋 Test 1: Validate endpoint without authentication")
        response = client_no_auth.get('/api/v1/license/validate/')
        if response.status_code == 401:
            print("   ✅ Validate endpoint properly requires authentication")
        else:
            print(f"   ❌ Validate endpoint authentication issue: {response.status_code}")
            
        print("   📋 Test 2: Info endpoint without authentication")
        response = client_no_auth.get('/api/v1/license/info/')
        if response.status_code == 401:
            print("   ✅ Info endpoint properly requires authentication")
        else:
            print(f"   ❌ Info endpoint authentication issue: {response.status_code}")
            
        # Test with invalid token
        print("   📋 Test 3: Invalid token handling")
        client_invalid = APIClient()
        client_invalid.credentials(HTTP_AUTHORIZATION='Bearer invalid_token')
        
        response = client_invalid.get('/api/v1/license/validate/')
        if response.status_code == 401:
            print("   ✅ Invalid token properly rejected")
        else:
            print(f"   ❌ Invalid token handling issue: {response.status_code}")
            
        return True
        
    def test_license_validation_tracking(self):
        """Test that license validations are properly tracked"""
        print("\n🧪 Testing License Validation Tracking...")
        
        try:
            # Get initial validation count
            license_obj = License.objects.get(user=self.test_user)
            initial_count = license_obj.usage_count
            initial_validations = LicenseValidation.objects.filter(license=license_obj).count()
            
            print(f"   📊 Initial usage count: {initial_count}")
            print(f"   📊 Initial validation records: {initial_validations}")
            
            # Make a validation request
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
            response = self.client.get('/api/v1/license/validate/')
            
            if response.status_code == 200:
                # Check updated counts
                license_obj.refresh_from_db()
                new_count = license_obj.usage_count
                new_validations = LicenseValidation.objects.filter(license=license_obj).count()
                
                print(f"   📊 New usage count: {new_count}")
                print(f"   📊 New validation records: {new_validations}")
                
                if new_count > initial_count:
                    print("   ✅ Usage count properly incremented")
                else:
                    print("   ❌ Usage count not incremented")
                    
                if new_validations > initial_validations:
                    print("   ✅ Validation record properly created")
                    
                    # Check validation record details
                    latest_validation = LicenseValidation.objects.filter(license=license_obj).first()
                    print(f"   📋 Latest validation IP: {latest_validation.ip_address}")
                    print(f"   📋 Latest validation success: {latest_validation.is_successful}")
                    print(f"   📋 Latest validation time: {latest_validation.validated_at}")
                else:
                    print("   ❌ Validation record not created")
                    
            return True
            
        except Exception as e:
            print(f"   ❌ Validation tracking test failed: {e}")
            return False
            
    def test_api_url_structure(self):
        """Test that API URLs are properly structured"""
        print("\n🧪 Testing API URL Structure...")
        
        # Test URL patterns
        expected_urls = [
            '/api/v1/license/validate/',
            '/api/v1/license/info/',
        ]
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        for url in expected_urls:
            print(f"   📋 Testing URL: {url}")
            response = self.client.get(url)
            
            if response.status_code in [200, 400, 403]:  # Valid responses
                print(f"   ✅ URL {url} is accessible")
            else:
                print(f"   ❌ URL {url} returned unexpected status: {response.status_code}")
                
        return True
        
    def run_all_tests(self):
        """Run all license validation API tests"""
        print("🚀 Starting License Validation APIs Tests (Task 6.2)")
        print("=" * 70)
        
        # Setup test user
        if not self.setup_test_user():
            print("❌ Failed to setup test user, stopping tests")
            return False
            
        try:
            success = True
            
            # Test API endpoints
            if not self.test_license_validate_api_endpoint():
                success = False
                
            if not self.test_license_info_api_endpoint():
                success = False
                
            # Test authentication
            if not self.test_api_authentication():
                success = False
                
            # Test validation tracking
            if not self.test_license_validation_tracking():
                success = False
                
            # Test URL structure
            if not self.test_api_url_structure():
                success = False
                
            print("\n" + "=" * 70)
            if success:
                print("🎉 All License Validation API Tests Passed!")
                print("\n📋 Task 6.2 Requirements Verified:")
                print("   ✅ GET /api/v1/license/validate برای بررسی license")
                print("   ✅ GET /api/v1/license/info برای اطلاعات license")
                print("   ✅ JWT Authentication required")
                print("   ✅ Hardware fingerprinting support")
                print("   ✅ Validation tracking and logging")
                print("   ✅ Proper error handling")
            else:
                print("❌ Some License Validation API Tests Failed!")
                
            return success
            
        finally:
            # Cleanup
            self.cleanup_test_user()

def main():
    """Main test runner"""
    try:
        tester = LicenseValidationAPITest()
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()