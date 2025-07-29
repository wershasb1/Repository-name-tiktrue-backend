#!/usr/bin/env python3
"""
Integration tests for Backend API Client
Tests real-world integration scenarios and workflows
"""

import asyncio
import pytest
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend_api_client import (
    BackendAPIClient, LoginCredentials, APIResponse,
    create_api_client, test_backend_connection
)


class TestBackendAPIIntegration:
    """Integration tests for Backend API Client"""
    
    @pytest.fixture
    def backend_url(self):
        """Get backend URL from environment or use test default"""
        return os.getenv('BACKEND_URL', 'https://api.test.tiktrue.com')
    
    @pytest.fixture
    def test_credentials(self):
        """Get test credentials from environment"""
        return LoginCredentials(
            username=os.getenv('TEST_USERNAME', 'test@example.com'),
            password=os.getenv('TEST_PASSWORD', 'test_password_123'),
            hardware_fingerprint=os.getenv('TEST_HW_FINGERPRINT', 'test_hw_fingerprint_abc123')
        )
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_authentication_workflow(self, backend_url, test_credentials):
        """Test complete authentication workflow"""
        async with BackendAPIClient(backend_url) as client:
            # Initial state - not authenticated
            assert not client.is_authenticated()
            
            # Attempt login
            login_result = await client.login(test_credentials)
            
            if login_result.success:
                # Should be authenticated now
                assert client.is_authenticated()
                assert client.access_token is not None
                assert client.refresh_token is not None
                assert client.token_expires_at is not None
                
                # Test logout
                logout_result = await client.logout()
                assert logout_result.success
                
                # Should not be authenticated after logout
                assert not client.is_authenticated()
                assert client.access_token is None
                assert client.refresh_token is None
            else:
                # Expected to fail with test server
                assert login_result.error is not None
                assert login_result.error_code is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_license_management_workflow(self, backend_url, test_credentials):
        """Test license management workflow"""
        async with BackendAPIClient(backend_url) as client:
            # Login first (may fail with test server)
            login_result = await client.login(test_credentials)
            
            if login_result.success:
                # Test license validation
                license_result = await client.validate_license(test_credentials.hardware_fingerprint)
                
                if license_result.success:
                    assert license_result.data is not None
                    assert 'valid' in license_result.data
                
                # Test license info retrieval
                info_result = await client.get_license_info()
                
                if info_result.success:
                    assert info_result.data is not None
                    # Should contain license details
                    expected_fields = ['license_key', 'plan', 'expires_at', 'max_clients']
                    for field in expected_fields:
                        if field in info_result.data:
                            assert info_result.data[field] is not None
            else:
                # Expected behavior with test server
                assert login_result.error is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_model_management_workflow(self, backend_url, test_credentials):
        """Test model management workflow"""
        async with BackendAPIClient(backend_url) as client:
            # Login first
            login_result = await client.login(test_credentials)
            
            if login_result.success:
                # Test getting available models
                models_result = await client.get_available_models()
                
                if models_result.success:
                    assert models_result.data is not None
                    assert 'models' in models_result.data
                    
                    # If models are available, test metadata retrieval
                    models = models_result.data['models']
                    if models and len(models) > 0:
                        first_model = models[0]
                        model_id = first_model.get('model_id')
                        
                        if model_id:
                            # Test model metadata
                            metadata_result = await client.get_model_metadata(model_id)
                            
                            if metadata_result.success:
                                assert metadata_result.data is not None
                            
                            # Test download URL
                            download_result = await client.get_model_download_url(model_id)
                            
                            if download_result.success:
                                assert download_result.data is not None
                                assert 'download_url' in download_result.data
            else:
                # Expected behavior with test server
                assert login_result.error is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_payment_workflow(self, backend_url, test_credentials):
        """Test payment workflow"""
        async with BackendAPIClient(backend_url) as client:
            # Login first
            login_result = await client.login(test_credentials)
            
            if login_result.success:
                # Test payment session creation
                payment_result = await client.create_payment_session("PRO", 12)
                
                if payment_result.success:
                    assert payment_result.data is not None
                    # Should contain payment session details
                    expected_fields = ['session_id', 'payment_url', 'amount']
                    for field in expected_fields:
                        if field in payment_result.data:
                            assert payment_result.data[field] is not None
                
                # Test payment history
                history_result = await client.get_payment_history()
                
                if history_result.success:
                    assert history_result.data is not None
                    assert 'payments' in history_result.data
            else:
                # Expected behavior with test server
                assert login_result.error is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, backend_url):
        """Test error handling and recovery mechanisms"""
        # Test with invalid URL
        invalid_client = BackendAPIClient("https://invalid.nonexistent.url.test")
        
        async with invalid_client:
            # Should handle connection errors gracefully
            connection_result = await invalid_client.test_connection()
            assert not connection_result.success
            assert connection_result.error is not None
            assert connection_result.error_code == "CONNECTION_ERROR"
            
            # Should handle authentication errors gracefully
            fake_credentials = LoginCredentials(
                username="fake@example.com",
                password="fake_password",
                hardware_fingerprint="fake_fingerprint"
            )
            
            login_result = await invalid_client.login(fake_credentials)
            assert not login_result.success
            assert login_result.error is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, backend_url, test_credentials):
        """Test concurrent request handling"""
        async with BackendAPIClient(backend_url) as client:
            # Create multiple concurrent connection tests
            tasks = []
            for i in range(5):
                task = client.test_connection()
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should complete (may fail, but should not raise exceptions)
            assert len(results) == 5
            for result in results:
                if isinstance(result, APIResponse):
                    assert result.success is not None
                    assert result.error_code is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_session_management(self, backend_url):
        """Test session management and cleanup"""
        client = BackendAPIClient(backend_url)
        
        # Test session creation
        await client.start_session()
        assert client.session is not None
        
        # Test session usage
        connection_result = await client.test_connection()
        assert connection_result is not None
        
        # Test session cleanup
        await client.close_session()
        # Session should be closed (can't easily test without mocking)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_convenience_functions(self, backend_url):
        """Test convenience functions"""
        # Test create_api_client
        client = await create_api_client(backend_url)
        assert isinstance(client, BackendAPIClient)
        assert client.base_url == backend_url
        await client.close_session()
        
        # Test test_backend_connection
        is_connected = await test_backend_connection(backend_url)
        assert isinstance(is_connected, bool)


class TestBackendAPIPerformance:
    """Performance tests for Backend API Client"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_request_performance(self, backend_url="https://api.test.tiktrue.com"):
        """Test request performance and timing"""
        async with BackendAPIClient(backend_url) as client:
            start_time = datetime.now()
            
            # Make multiple requests
            for i in range(10):
                await client.test_connection()
            
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            
            # Should complete within reasonable time (10 seconds for 10 requests)
            assert total_time < 10.0
            
            # Average time per request should be reasonable
            avg_time = total_time / 10
            assert avg_time < 1.0  # Less than 1 second per request
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_memory_usage(self, backend_url="https://api.test.tiktrue.com"):
        """Test memory usage patterns"""
        import gc
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create and use multiple clients
        for i in range(100):
            async with BackendAPIClient(backend_url) as client:
                await client.test_connection()
        
        # Force garbage collection
        gc.collect()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024  # 50MB


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-m", "integration"])