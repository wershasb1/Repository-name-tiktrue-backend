#!/usr/bin/env python3
"""
Test script for TikTrue Backend API
Tests all endpoints to ensure they work correctly
"""

import requests
import json
import sys

# API Base URL
# BASE_URL = "https://tiktrue-backend.liara.run"
BASE_URL = "https://tiktrue.com"  # Using custom domain

class TikTrueAPITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None
        
    def test_health(self):
        """Test if server is running"""
        print("🔍 Testing server health...")
        try:
            response = self.session.get(f"{self.base_url}/admin/")
            if response.status_code == 200:
                print("✅ Server is running!")
                return True
            else:
                print(f"❌ Server returned status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Server connection failed: {e}")
            return False
    
    def test_register(self):
        """Test user registration"""
        print("\n🔍 Testing user registration...")
        
        data = {
            "email": "test@tiktrue.com",
            "username": "testuser",
            "password": "testpass123",
            "password_confirm": "testpass123"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/register/",
                json=data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                result = response.json()
                self.access_token = result['tokens']['access']
                self.refresh_token = result['tokens']['refresh']
                print("✅ User registration successful!")
                print(f"   User ID: {result['user']['id']}")
                print(f"   Email: {result['user']['email']}")
                return True
            else:
                print(f"❌ Registration failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False
    
    def test_login(self):
        """Test user login"""
        print("\n🔍 Testing user login...")
        
        data = {
            "email": "test@tiktrue.com",
            "password": "testpass123",
            "hardware_fingerprint": "test-hardware-123"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login/",
                json=data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result['tokens']['access']
                self.refresh_token = result['tokens']['refresh']
                print("✅ User login successful!")
                print(f"   Plan: {result['user']['subscription_plan']}")
                print(f"   Max clients: {result['user']['max_clients']}")
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def test_profile(self):
        """Test user profile"""
        print("\n🔍 Testing user profile...")
        
        if not self.access_token:
            print("❌ No access token available")
            return False
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/auth/profile/",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Profile retrieved successfully!")
                print(f"   Email: {result['email']}")
                print(f"   Plan: {result['subscription_plan']}")
                print(f"   Allowed models: {result['allowed_models']}")
                return True
            else:
                print(f"❌ Profile failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Profile error: {e}")
            return False
    
    def test_license_validation(self):
        """Test license validation"""
        print("\n🔍 Testing license validation...")
        
        if not self.access_token:
            print("❌ No access token available")
            return False
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/license/validate/?hardware_fingerprint=test-hardware-123",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ License validation successful!")
                print(f"   Valid: {result['valid']}")
                print(f"   License key: {result['license']['license_key'][:16]}...")
                return True
            else:
                print(f"❌ License validation failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ License validation error: {e}")
            return False
    
    def test_available_models(self):
        """Test available models"""
        print("\n🔍 Testing available models...")
        
        if not self.access_token:
            print("❌ No access token available")
            return False
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/models/available/",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Available models retrieved!")
                print(f"   Total models: {result['total_models']}")
                print(f"   User plan: {result['user_plan']}")
                for model in result['models']:
                    print(f"   - {model['display_name']} ({model['name']})")
                return True
            else:
                print(f"❌ Available models failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Available models error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting TikTrue Backend API Tests")
        print("=" * 50)
        
        tests = [
            self.test_health,
            self.test_register,
            self.test_login,
            self.test_profile,
            self.test_license_validation,
            self.test_available_models
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            if test():
                passed += 1
        
        print("\n" + "=" * 50)
        print(f"🎯 Test Results: {passed}/{total} passed")
        
        if passed == total:
            print("🎉 All tests passed! Backend is working correctly!")
            return True
        else:
            print("❌ Some tests failed. Please check the backend.")
            return False

if __name__ == "__main__":
    # You can change the URL here
    url = BASE_URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    tester = TikTrueAPITester(url)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)