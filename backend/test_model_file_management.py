#!/usr/bin/env python
"""
Test script for Model File Management System
Tests secure storage, access control, and usage analytics
"""

import os
import sys
import django
from pathlib import Path

# Add the backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktrue_backend.settings')
django.setup()

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import json

from models_api.models import ModelFile, ModelAccess, ModelDownload
from models_api.storage import SecureModelStorage, AuthenticatedDownloadManager
from models_api.access_control import ModelAccessController, ModelUsageAnalytics

User = get_user_model()

class ModelFileManagementTest:
    """Test suite for model file management system"""
    
    def __init__(self):
        self.storage = SecureModelStorage()
        self.download_manager = AuthenticatedDownloadManager()
        self.access_controller = ModelAccessController()
        self.analytics = ModelUsageAnalytics()
        
        print("🚀 Starting Model File Management Tests")
        print("=" * 50)
    
    def setup_test_data(self):
        """Setup test users and models"""
        print("\n📋 Setting up test data...")
        
        # Create test users with different subscription plans
        self.free_user = User.objects.create_user(
            username='free_user',
            email='free@test.com',
            password='testpass123'
        )
        self.free_user.subscription_plan = 'free'
        self.free_user.subscription_expires = timezone.now() + timedelta(days=30)
        self.free_user.save()
        
        self.pro_user = User.objects.create_user(
            username='pro_user',
            email='pro@test.com',
            password='testpass123'
        )
        self.pro_user.subscription_plan = 'pro'
        self.pro_user.subscription_expires = timezone.now() + timedelta(days=30)
        self.pro_user.save()
        
        self.enterprise_user = User.objects.create_user(
            username='enterprise_user',
            email='enterprise@test.com',
            password='testpass123'
        )
        self.enterprise_user.subscription_plan = 'enterprise'
        self.enterprise_user.subscription_expires = timezone.now() + timedelta(days=365)
        self.enterprise_user.save()
        
        # Get or create test models
        self.llama_model, created = ModelFile.objects.get_or_create(
            name='llama3_1_8b_fp16',
            defaults={
                'display_name': 'Llama 3.1 8B FP16',
                'description': 'Test Llama model',
                'version': '1.0.0',
                'file_size': 8000000000,  # 8GB
                'block_count': 33,
                'is_active': True
            }
        )
        
        self.mistral_model, created = ModelFile.objects.get_or_create(
            name='mistral_7b_int4',
            defaults={
                'display_name': 'Mistral 7B INT4',
                'description': 'Test Mistral model',
                'version': '1.0.0',
                'file_size': 4000000000,  # 4GB
                'block_count': 32,
                'is_active': True
            }
        )
        
        print("✅ Test data setup complete")
    
    def test_secure_storage(self):
        """Test secure model storage functionality"""
        print("\n🔒 Testing Secure Storage System...")
        
        # Test model metadata storage
        test_metadata = {
            'model_type': 'llama',
            'num_layers': 32,
            'test_data': True
        }
        
        success = self.storage.store_model_metadata('test_model', test_metadata)
        assert success, "Failed to store model metadata"
        print("✅ Model metadata storage: PASSED")
        
        # Test metadata retrieval
        retrieved_metadata = self.storage.retrieve_model_metadata('test_model')
        assert retrieved_metadata == test_metadata, "Metadata mismatch"
        print("✅ Model metadata retrieval: PASSED")
        
        # Test model block storage
        test_block_data = b"This is test model block data" * 1000  # Simulate block data
        test_block_metadata = {'block_id': 1, 'test': True}
        
        result = self.storage.store_model_block('test_model', 1, test_block_data, test_block_metadata)
        assert result['success'], f"Failed to store model block: {result.get('error')}"
        print("✅ Model block storage: PASSED")
        
        # Test block retrieval
        retrieved_block = self.storage.retrieve_model_block('test_model', 1)
        assert retrieved_block == test_block_data, "Block data mismatch"
        print("✅ Model block retrieval: PASSED")
        
        # Test storage statistics
        stats = self.storage.get_storage_stats('test_model')
        assert stats['exists'], "Storage stats should show model exists"
        assert stats['block_count'] == 1, "Block count mismatch"
        print("✅ Storage statistics: PASSED")
        
        print("🔒 Secure Storage System: ALL TESTS PASSED")
    
    def test_access_control(self):
        """Test model access control system"""
        print("\n🛡️ Testing Access Control System...")
        
        # Test free user access
        access_result = self.access_controller.check_model_access(self.free_user, 'llama3_1_8b_fp16')
        print(f"Free user access result: {access_result}")
        assert access_result['allowed'], f"Free user should have access to Llama model: {access_result.get('message', 'No message')}"
        print("✅ Free user Llama access: PASSED")
        
        access_result = self.access_controller.check_model_access(self.free_user, 'mistral_7b_int4')
        assert not access_result['allowed'], "Free user should not have access to Mistral model"
        print("✅ Free user Mistral restriction: PASSED")
        
        # Test pro user access
        access_result = self.access_controller.check_model_access(self.pro_user, 'llama3_1_8b_fp16')
        assert access_result['allowed'], "Pro user should have access to Llama model"
        print("✅ Pro user Llama access: PASSED")
        
        access_result = self.access_controller.check_model_access(self.pro_user, 'mistral_7b_int4')
        assert access_result['allowed'], "Pro user should have access to Mistral model"
        print("✅ Pro user Mistral access: PASSED")
        
        # Test enterprise user access
        access_result = self.access_controller.check_model_access(self.enterprise_user, 'llama3_1_8b_fp16')
        assert access_result['allowed'], "Enterprise user should have access to all models"
        print("✅ Enterprise user access: PASSED")
        
        # Test access summary
        summary = self.access_controller.get_user_access_summary(self.pro_user)
        assert summary['subscription_plan'] == 'pro', "Subscription plan mismatch"
        assert 'model_access' in summary, "Model access info missing"
        print("✅ Access summary generation: PASSED")
        
        print("🛡️ Access Control System: ALL TESTS PASSED")
    
    def test_download_management(self):
        """Test authenticated download management"""
        print("\n📥 Testing Download Management...")
        
        # Test download URL creation
        download_token = self.download_manager.create_download_url(
            self.pro_user, 'llama3_1_8b_fp16', expires_in=3600
        )
        assert download_token, "Failed to create download token"
        print("✅ Download token creation: PASSED")
        
        # Test token validation
        token_data = self.download_manager.validate_download_token(
            download_token, self.pro_user.id, '127.0.0.1'
        )
        assert token_data, "Failed to validate download token"
        assert token_data['model_name'] == 'llama3_1_8b_fp16', "Model name mismatch"
        print("✅ Download token validation: PASSED")
        
        # Test invalid token
        invalid_token_data = self.download_manager.validate_download_token(
            'invalid_token', self.pro_user.id, '127.0.0.1'
        )
        assert not invalid_token_data, "Invalid token should not validate"
        print("✅ Invalid token rejection: PASSED")
        
        print("📥 Download Management: ALL TESTS PASSED")
    
    def test_usage_analytics(self):
        """Test usage analytics system"""
        print("\n📊 Testing Usage Analytics...")
        
        # Create some test download records
        ModelDownload.objects.create(
            user=self.pro_user,
            model=self.llama_model,
            download_token='test_token_1',
            ip_address='127.0.0.1',
            is_completed=True,
            completed_at=timezone.now()
        )
        
        ModelDownload.objects.create(
            user=self.pro_user,
            model=self.mistral_model,
            download_token='test_token_2',
            ip_address='127.0.0.1',
            is_completed=True,
            completed_at=timezone.now()
        )
        
        # Test user usage statistics
        user_stats = self.analytics.get_user_usage_stats(self.pro_user, days=30)
        assert user_stats['total_downloads'] >= 2, "Download count mismatch"
        assert user_stats['unique_models_accessed'] >= 2, "Unique models count mismatch"
        print("✅ User usage statistics: PASSED")
        
        # Test model usage statistics
        model_stats = self.analytics.get_model_usage_stats('llama3_1_8b_fp16', days=30)
        assert model_stats['total_downloads'] >= 1, "Model download count mismatch"
        print("✅ Model usage statistics: PASSED")
        
        # Test system overview
        system_overview = self.analytics.get_system_usage_overview(days=30)
        assert system_overview['total_downloads'] >= 2, "System download count mismatch"
        print("✅ System usage overview: PASSED")
        
        print("📊 Usage Analytics: ALL TESTS PASSED")
    
    def test_integration(self):
        """Test full integration workflow"""
        print("\n🔄 Testing Integration Workflow...")
        
        # Simulate full download workflow
        # 1. Check access
        access_result = self.access_controller.check_model_access(self.pro_user, 'llama3_1_8b_fp16')
        assert access_result['allowed'], "Access check failed"
        
        # 2. Create download token
        download_token = self.download_manager.create_download_url(
            self.pro_user, 'llama3_1_8b_fp16'
        )
        assert download_token, "Download token creation failed"
        
        # 3. Record download attempt
        success = self.access_controller.record_download_attempt(
            self.pro_user, 'llama3_1_8b_fp16', True, '127.0.0.1'
        )
        assert success, "Download attempt recording failed"
        
        # 4. Verify analytics updated
        user_stats = self.analytics.get_user_usage_stats(self.pro_user)
        assert user_stats['total_downloads'] > 0, "Analytics not updated"
        
        print("✅ Full integration workflow: PASSED")
        print("🔄 Integration Workflow: ALL TESTS PASSED")
    
    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n🧹 Cleaning up test data...")
        
        # Delete test users
        User.objects.filter(username__in=['free_user', 'pro_user', 'enterprise_user']).delete()
        
        # Delete test models
        ModelFile.objects.filter(name__in=['test_model']).delete()
        
        # Clean up test storage
        try:
            self.storage.delete_model('test_model')
        except:
            pass
        
        print("✅ Cleanup complete")
    
    def run_all_tests(self):
        """Run all tests"""
        try:
            self.setup_test_data()
            self.test_secure_storage()
            self.test_access_control()
            self.test_download_management()
            self.test_usage_analytics()
            self.test_integration()
            
            print("\n" + "=" * 50)
            print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
            print("✅ Secure Model Storage System: Working")
            print("✅ Access Control System: Working")
            print("✅ Download Management: Working")
            print("✅ Usage Analytics: Working")
            print("✅ Full Integration: Working")
            print("=" * 50)
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            self.cleanup_test_data()

if __name__ == '__main__':
    test_suite = ModelFileManagementTest()
    test_suite.run_all_tests()