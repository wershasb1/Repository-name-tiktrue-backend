#!/usr/bin/env python3
"""
Simple test for License Management System
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
from licenses.models import License
from licenses.hardware_fingerprint import generate_hardware_fingerprint

User = get_user_model()

def test_license_system():
    print("🧪 Testing License Management System...")
    
    # Create test user
    user = User.objects.create_user(
        email='test@example.com',
        username='testuser',
        password='testpass123'
    )
    print(f"✅ Created test user: {user.email}")
    
    # Create license
    license_obj = License.objects.create(user=user)
    print(f"✅ Created license: {license_obj.license_key}")
    
    # Test license validation
    is_valid = license_obj.is_valid()
    print(f"✅ License is valid: {is_valid}")
    
    # Test hardware fingerprint
    try:
        fingerprint = generate_hardware_fingerprint()
        print(f"✅ Generated hardware fingerprint: {fingerprint[:16]}...")
    except Exception as e:
        print(f"❌ Hardware fingerprint generation failed: {e}")
    
    # Test API
    client = APIClient()
    
    # Login
    login_response = client.post('/api/v1/auth/login/', {
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    
    if login_response.status_code == 200:
        token = login_response.json()['tokens']['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Test license validation API
        response = client.get('/api/v1/license/validate/')
        print(f"License validation API response: {response.status_code}")
        if response.status_code in [200, 403]:
            print(f"✅ License validation API working: {response.json()}")
        else:
            print(f"❌ License validation API failed: {response.json()}")
            
        # Test license info API
        response = client.get('/api/v1/license/info/')
        print(f"License info API response: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ License info API working")
        else:
            print(f"❌ License info API failed: {response.json()}")
    else:
        print(f"❌ Login failed: {login_response.json()}")
    
    # Cleanup
    user.delete()
    print("✅ Cleaned up test data")
    
    print("🎉 License system test completed!")

if __name__ == "__main__":
    test_license_system()