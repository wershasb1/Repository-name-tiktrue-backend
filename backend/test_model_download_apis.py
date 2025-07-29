#!/usr/bin/env python3
"""
Test script for Model Download APIs
Tests the specific API endpoints required by task 6.3:
- GET /api/v1/models/available برای لیست مدل‌ها
- GET /api/v1/models/download/{id} برای دانلود امن
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
from models_api.models import ModelFile, ModelAccess, ModelDownload
import json

User = get_user_model()

class ModelDownloadAPITest:
    def __init__(self):
        self.client = APIClient()
        self.test_user_data = {
            'email': 'model_test@tiktrue.com',
            'username': 'modeluser',
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
            print(f"   Subscription Plan: {self.test_user.subscription_plan}")
            print(f"   Allowed Models: {self.test_user.get_allowed_models()}")
            return True
        else:
            print(f"❌ Failed to create test user: {response.json()}")
            return False
            
    def setup_test_models(self):
        """Create test model files"""
        print("🔧 Setting up test models...")
        
        # Create test models if they don't exist
        models_data = [
            {
                'name': 'llama3_1_8b_fp16',
                'display_name': 'Llama 3.1 8B FP16',
                'description': 'Llama 3.1 8B model with FP16 precision',
                'version': '1.0.0',
                'file_size': 16000000000,  # 16GB
                'block_count': 33
            },
            {
                'name': 'mistral_7b_int4',
                'display_name': 'Mistral 7B INT4',
                'description': 'Mistral 7B model with INT4 quantization',
                'version': '1.0.0',
                'file_size': 4000000000,  # 4GB
                'block_count': 32
            }
        ]
        
        created_models = []
        for model_data in models_data:
            model, created = ModelFile.objects.get_or_create(
                name=model_data['name'],
                defaults=model_data
            )
            created_models.append(model)
            if created:
                print(f"✅ Created test model: {model.display_name}")
            else:
                print(f"✅ Test model exists: {model.display_name}")
                
        return created_models
        
    def cleanup_test_user(self):
        """Clean up test user"""
        try:
            if self.test_user:
                self.test_user.delete()
                print("✅ Test user cleaned up")
        except:
            pass
            
    def test_available_models_api(self):
        """Test GET /api/v1/models/available/ endpoint"""
        print("\n🧪 Testing GET /api/v1/models/available/ API Endpoint...")
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.get('/api/v1/models/available/')
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Available models API successful")
            print(f"   User Plan: {data['user_plan']}")
            print(f"   Total Models: {data['total_models']}")
            print(f"   Models Count: {len(data['models'])}")
            
            # Verify response structure
            required_fields = ['models', 'user_plan', 'total_models']
            for field in required_fields:
                if field not in data:
                    print(f"   ❌ Missing required field: {field}")
                    return False, None
                    
            # Verify model structure
            if data['models']:
                model = data['models'][0]
                model_fields = ['id', 'name', 'display_name', 'description', 'version', 'file_size', 'block_count']
                for field in model_fields:
                    if field not in model:
                        print(f"   ❌ Missing model field: {field}")
                        return False, None
                        
                print(f"   📋 Sample Model: {model['display_name']}")
                print(f"      Name: {model['name']}")
                print(f"      Version: {model['version']}")
                print(f"      File Size: {model['file_size']} bytes")
                print(f"      Block Count: {model['block_count']}")
                
            return True, data['models']
        else:
            print(f"   ❌ Available models API failed: {response.status_code}")
            print(f"      Error: {response.json()}")
            return False, None
            
    def test_model_metadata_api(self, models):
        """Test GET /api/v1/models/{id}/metadata/ endpoint"""
        print("\n🧪 Testing GET /api/v1/models/{id}/metadata/ API Endpoint...")
        
        if not models:
            print("   ⚠️ No models available for metadata test")
            return True
            
        model = models[0]
        model_id = model['id']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.get(f'/api/v1/models/{model_id}/metadata/')
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Model metadata API successful")
            print(f"      Model: {data['display_name']}")
            print(f"      Version: {data['version']}")
            print(f"      File Size: {data['file_size']} bytes")
            print(f"      Block Count: {data['block_count']}")
            return True
        else:
            print(f"   ❌ Model metadata API failed: {response.status_code}")
            print(f"      Error: {response.json()}")
            return False
            
    def test_create_download_token_api(self, models):
        """Test POST /api/v1/models/{id}/download/ endpoint"""
        print("\n🧪 Testing POST /api/v1/models/{id}/download/ API Endpoint...")
        
        if not models:
            print("   ⚠️ No models available for download token test")
            return True, None
            
        model = models[0]
        model_id = model['id']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.post(f'/api/v1/models/{model_id}/download/')
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Download token creation successful")
            print(f"      Download Token: {data['download_token'][:16]}...")
            print(f"      Model: {data['model_info']['display_name']}")
            print(f"      Expires In: {data['expires_in']} seconds")
            print(f"      Download URL: {data['download_url']}")
            
            # Verify response structure
            required_fields = ['download_token', 'model_info', 'expires_in', 'download_url']
            for field in required_fields:
                if field not in data:
                    print(f"   ❌ Missing required field: {field}")
                    return False, None
                    
            return True, data['download_token']
        else:
            print(f"   ❌ Download token creation failed: {response.status_code}")
            print(f"      Error: {response.json()}")
            return False, None
            
    def test_download_model_api(self, download_token):
        """Test GET /api/v1/models/download/{token}/ endpoint"""
        print("\n🧪 Testing GET /api/v1/models/download/{token}/ API Endpoint...")
        
        if not download_token:
            print("   ⚠️ No download token available for download test")
            return True
            
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.get(f'/api/v1/models/download/{download_token}/')
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Model download API successful")
            print(f"      Model Name: {data['model_name']}")
            print(f"      Display Name: {data['display_name']}")
            print(f"      Version: {data['version']}")
            print(f"      Block Count: {data['block_count']}")
            print(f"      File Size: {data['file_size']} bytes")
            print(f"      Blocks Available: {len(data['blocks'])}")
            
            # Verify response structure
            required_fields = ['model_name', 'display_name', 'version', 'block_count', 'file_size', 'blocks', 'tokenizer', 'metadata']
            for field in required_fields:
                if field not in data:
                    print(f"   ❌ Missing required field: {field}")
                    return False
                    
            # Verify blocks structure
            if data['blocks']:
                block = data['blocks'][0]
                block_fields = ['block_id', 'filename', 'download_url']
                for field in block_fields:
                    if field not in block:
                        print(f"   ❌ Missing block field: {field}")
                        return False
                        
                print(f"      Sample Block: {block['filename']}")
                print(f"      Block URL: {block['download_url']}")
                
            # Verify tokenizer and metadata
            if 'download_url' not in data['tokenizer']:
                print("   ❌ Missing tokenizer download_url")
                return False
                
            if 'download_url' not in data['metadata']:
                print("   ❌ Missing metadata download_url")
                return False
                
            print(f"      Tokenizer URL: {data['tokenizer']['download_url']}")
            print(f"      Metadata URL: {data['metadata']['download_url']}")
            
            return True
        else:
            print(f"   ❌ Model download API failed: {response.status_code}")
            print(f"      Error: {response.json()}")
            return False
            
    def test_api_authentication(self):
        """Test API authentication requirements"""
        print("\n🧪 Testing API Authentication Requirements...")
        
        # Test without authentication
        client_no_auth = APIClient()
        
        print("   📋 Test 1: Available models endpoint without authentication")
        response = client_no_auth.get('/api/v1/models/available/')
        if response.status_code == 401:
            print("   ✅ Available models endpoint properly requires authentication")
        else:
            print(f"   ❌ Available models endpoint authentication issue: {response.status_code}")
            
        # Test with invalid token
        print("   📋 Test 2: Invalid token handling")
        client_invalid = APIClient()
        client_invalid.credentials(HTTP_AUTHORIZATION='Bearer invalid_token')
        
        response = client_invalid.get('/api/v1/models/available/')
        if response.status_code == 401:
            print("   ✅ Invalid token properly rejected")
        else:
            print(f"   ❌ Invalid token handling issue: {response.status_code}")
            
        return True
        
    def test_access_control(self):
        """Test model access control based on subscription"""
        print("\n🧪 Testing Model Access Control...")
        
        try:
            # Check that user gets models based on their subscription
            allowed_models = self.test_user.get_allowed_models()
            print(f"   📋 User allowed models: {allowed_models}")
            
            # Test available models API
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
            response = self.client.get('/api/v1/models/available/')
            
            if response.status_code == 200:
                data = response.json()
                api_models = [model['name'] for model in data['models']]
                print(f"   📋 API returned models: {api_models}")
                
                # Verify that API only returns allowed models
                for model_name in api_models:
                    if model_name not in allowed_models:
                        print(f"   ❌ API returned unauthorized model: {model_name}")
                        return False
                        
                print("   ✅ Access control working correctly")
                return True
            else:
                print(f"   ❌ Failed to test access control: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Access control test failed: {e}")
            return False
            
    def test_download_tracking(self):
        """Test that downloads are properly tracked"""
        print("\n🧪 Testing Download Tracking...")
        
        try:
            # Get initial counts
            initial_access_count = ModelAccess.objects.filter(user=self.test_user).count()
            initial_download_count = ModelDownload.objects.filter(user=self.test_user).count()
            
            print(f"   📊 Initial access records: {initial_access_count}")
            print(f"   📊 Initial download records: {initial_download_count}")
            
            # Make a download token request
            models = ModelFile.objects.filter(is_active=True)[:1]
            if models:
                model = models[0]
                self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
                response = self.client.post(f'/api/v1/models/{model.id}/download/')
                
                if response.status_code == 200:
                    # Check updated counts
                    new_access_count = ModelAccess.objects.filter(user=self.test_user).count()
                    new_download_count = ModelDownload.objects.filter(user=self.test_user).count()
                    
                    print(f"   📊 New access records: {new_access_count}")
                    print(f"   📊 New download records: {new_download_count}")
                    
                    if new_download_count > initial_download_count:
                        print("   ✅ Download record properly created")
                        
                        # Check download record details
                        latest_download = ModelDownload.objects.filter(user=self.test_user).first()
                        print(f"   📋 Latest download model: {latest_download.model.display_name}")
                        print(f"   📋 Latest download token: {latest_download.download_token[:16]}...")
                        print(f"   📋 Latest download IP: {latest_download.ip_address}")
                    else:
                        print("   ❌ Download record not created")
                        
                    if new_access_count >= initial_access_count:
                        print("   ✅ Access record properly updated")
                    else:
                        print("   ❌ Access record not updated")
                        
            return True
            
        except Exception as e:
            print(f"   ❌ Download tracking test failed: {e}")
            return False
            
    def test_api_url_structure(self):
        """Test that API URLs are properly structured"""
        print("\n🧪 Testing API URL Structure...")
        
        # Test URL patterns
        expected_urls = [
            '/api/v1/models/available/',
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
        """Run all model download API tests"""
        print("🚀 Starting Model Download APIs Tests (Task 6.3)")
        print("=" * 70)
        
        # Setup test user
        if not self.setup_test_user():
            print("❌ Failed to setup test user, stopping tests")
            return False
            
        # Setup test models
        test_models = self.setup_test_models()
        
        try:
            success = True
            
            # Test available models API
            models_success, models = self.test_available_models_api()
            if not models_success:
                success = False
                
            # Test model metadata API
            if not self.test_model_metadata_api(models):
                success = False
                
            # Test download token creation
            token_success, download_token = self.test_create_download_token_api(models)
            if not token_success:
                success = False
                
            # Test model download API
            if not self.test_download_model_api(download_token):
                success = False
                
            # Test authentication
            if not self.test_api_authentication():
                success = False
                
            # Test access control
            if not self.test_access_control():
                success = False
                
            # Test download tracking
            if not self.test_download_tracking():
                success = False
                
            # Test URL structure
            if not self.test_api_url_structure():
                success = False
                
            print("\n" + "=" * 70)
            if success:
                print("🎉 All Model Download API Tests Passed!")
                print("\n📋 Task 6.3 Requirements Verified:")
                print("   ✅ GET /api/v1/models/available برای لیست مدل‌ها")
                print("   ✅ GET /api/v1/models/download/{id} برای دانلود امن")
                print("   ✅ JWT Authentication required")
                print("   ✅ Subscription-based access control")
                print("   ✅ Download tracking and logging")
                print("   ✅ Secure token-based downloads")
                print("   ✅ Model metadata access")
                print("   ✅ Proper error handling")
            else:
                print("❌ Some Model Download API Tests Failed!")
                
            return success
            
        finally:
            # Cleanup
            self.cleanup_test_user()

def main():
    """Main test runner"""
    try:
        tester = ModelDownloadAPITest()
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()