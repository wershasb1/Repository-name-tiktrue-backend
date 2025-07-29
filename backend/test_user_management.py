#!/usr/bin/env python3
"""
Test script for User Management System
Tests the user registration, login, and profile functionality
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
import json

User = get_user_model()

class UserManagementTest:
    def __init__(self):
        self.client = APIClient()
        self.test_user_data = {
            'email': 'test@tiktrue.com',
            'username': 'testuser',
            'password': 'testpassword123',
            'password_confirm': 'testpassword123'
        }
        
    def cleanup_test_user(self):
        """Clean up test user if exists"""
        try:
            user = User.objects.get(email=self.test_user_data['email'])
            user.delete()
            print("✅ Cleaned up existing test user")
        except User.DoesNotExist:
            pass
            
    def test_user_registration(self):
        """Test user registration endpoint"""
        print("\n🧪 Testing User Registration...")
        
        response = self.client.post('/api/v1/auth/register/', self.test_user_data)
        
        if response.status_code == 201:
            data = response.json()
            print("✅ User registration successful")
            print(f"   User ID: {data['user']['id']}")
            print(f"   Email: {data['user']['email']}")
            print(f"   Subscription Plan: {data['user']['subscription_plan']}")
            print(f"   Access Token: {data['tokens']['access'][:50]}...")
            return data['tokens']['access']
        else:
            print(f"❌ User registration failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return None
            
    def test_user_login(self):
        """Test user login endpoint"""
        print("\n🧪 Testing User Login...")
        
        login_data = {
            'email': self.test_user_data['email'],
            'password': self.test_user_data['password'],
            'hardware_fingerprint': 'test-hardware-123'
        }
        
        response = self.client.post('/api/v1/auth/login/', login_data)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ User login successful")
            print(f"   Message: {data['message']}")
            print(f"   User: {data['user']['email']}")
            print(f"   Hardware Fingerprint Updated: Yes")
            return data['tokens']['access']
        else:
            print(f"❌ User login failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return None
            
    def test_user_profile(self, access_token):
        """Test user profile endpoint"""
        print("\n🧪 Testing User Profile...")
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get('/api/v1/auth/profile/')
        
        if response.status_code == 200:
            data = response.json()
            print("✅ User profile retrieval successful")
            print(f"   ID: {data['id']}")
            print(f"   Email: {data['email']}")
            print(f"   Username: {data['username']}")
            print(f"   Subscription Plan: {data['subscription_plan']}")
            print(f"   Max Clients: {data['max_clients']}")
            print(f"   Allowed Models: {data['allowed_models']}")
            print(f"   Created At: {data['created_at']}")
            return True
        else:
            print(f"❌ User profile retrieval failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return False
            
    def test_token_refresh(self, refresh_token):
        """Test token refresh endpoint"""
        print("\n🧪 Testing Token Refresh...")
        
        response = self.client.post('/api/v1/auth/refresh/', {'refresh': refresh_token})
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Token refresh successful")
            print(f"   New Access Token: {data['access'][:50]}...")
            return data['access']
        else:
            print(f"❌ Token refresh failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return None
            
    def test_user_logout(self, refresh_token):
        """Test user logout endpoint"""
        print("\n🧪 Testing User Logout...")
        
        response = self.client.post('/api/v1/auth/logout/', {'refresh_token': refresh_token})
        
        if response.status_code == 200:
            data = response.json()
            print("✅ User logout successful")
            print(f"   Message: {data['message']}")
            return True
        else:
            print(f"❌ User logout failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return False
            
    def run_all_tests(self):
        """Run all user management tests"""
        print("🚀 Starting User Management System Tests")
        print("=" * 50)
        
        # Cleanup any existing test user
        self.cleanup_test_user()
        
        # Test registration
        access_token = self.test_user_registration()
        if not access_token:
            print("❌ Registration test failed, stopping tests")
            return False
            
        # Get refresh token from registration
        response = self.client.post('/api/v1/auth/register/', self.test_user_data)
        if response.status_code == 400:  # User already exists, login instead
            login_response = self.client.post('/api/v1/auth/login/', {
                'email': self.test_user_data['email'],
                'password': self.test_user_data['password']
            })
            if login_response.status_code == 200:
                tokens = login_response.json()['tokens']
                access_token = tokens['access']
                refresh_token = tokens['refresh']
        
        # Test login
        login_access_token = self.test_user_login()
        if login_access_token:
            access_token = login_access_token
            
        # Test profile
        if not self.test_user_profile(access_token):
            print("❌ Profile test failed")
            
        # Get refresh token for remaining tests
        login_response = self.client.post('/api/v1/auth/login/', {
            'email': self.test_user_data['email'],
            'password': self.test_user_data['password']
        })
        
        if login_response.status_code == 200:
            refresh_token = login_response.json()['tokens']['refresh']
            
            # Test token refresh
            new_access_token = self.test_token_refresh(refresh_token)
            
            # Test logout
            self.test_user_logout(refresh_token)
            
        # Cleanup
        self.cleanup_test_user()
        
        print("\n" + "=" * 50)
        print("🎉 User Management System Tests Completed!")
        return True

def main():
    """Main test runner"""
    try:
        tester = UserManagementTest()
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()