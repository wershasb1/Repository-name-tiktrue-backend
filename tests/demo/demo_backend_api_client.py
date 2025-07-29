#!/usr/bin/env python3
"""
Demo script for Backend API Client
Shows real-world usage examples and integration patterns
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend_api_client import (
    BackendAPIClient, LoginCredentials, APIResponse,
    create_api_client, test_backend_connection
)


class BackendAPIDemo:
    """Demo class showing Backend API Client usage"""
    
    def __init__(self, base_url: str = "https://api.tiktrue.com"):
        self.base_url = base_url
        self.client: BackendAPIClient = None
    
    async def demo_initialization(self):
        """Demo: API client initialization"""
        print("🔧 Demo: API Client Initialization")
        print("-" * 40)
        
        # Create client
        self.client = BackendAPIClient(
            base_url=self.base_url,
            timeout=30,
            max_retries=3
        )
        
        print(f"✅ Client created with base URL: {self.client.base_url}")
        print(f"✅ Timeout: {self.client.timeout}s")
        print(f"✅ Max retries: {self.client.max_retries}")
        print(f"✅ Authentication status: {self.client.is_authenticated()}")
        print()
    
    async def demo_connection_test(self):
        """Demo: Connection testing"""
        print("🌐 Demo: Connection Testing")
        print("-" * 40)
        
        try:
            # Test connection using convenience function
            is_connected = await test_backend_connection(self.base_url)
            print(f"✅ Connection test result: {is_connected}")
            
            # Test connection using client method
            async with self.client:
                connection_result = await self.client.test_connection()
                print(f"✅ Client connection test: {connection_result.success}")
                if not connection_result.success:
                    print(f"   Error: {connection_result.error}")
        
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
        
        print()
    
    async def demo_authentication_flow(self):
        """Demo: Authentication workflow"""
        print("🔐 Demo: Authentication Flow")
        print("-" * 40)
        
        # Create test credentials
        credentials = LoginCredentials(
            username="demo@tiktrue.com",
            password="demo_password_123",
            hardware_fingerprint="demo_hw_fingerprint_abc123"
        )
        
        print(f"✅ Credentials created for: {credentials.username}")
        print(f"✅ Hardware fingerprint: {credentials.hardware_fingerprint[:20]}...")
        
        async with self.client:
            # Attempt login (will fail with demo server, but shows the flow)
            login_result = await self.client.login(credentials)
            
            if login_result.success:
                print("✅ Login successful!")
                print(f"   Access token: {self.client.access_token[:20]}...")
                print(f"   Token expires at: {self.client.token_expires_at}")
                
                # Test logout
                logout_result = await self.client.logout()
                print(f"✅ Logout result: {logout_result.success}")
            else:
                print(f"❌ Login failed (expected with demo): {login_result.error}")
        
        print()
    
    async def demo_license_operations(self):
        """Demo: License management operations"""
        print("📜 Demo: License Operations")
        print("-" * 40)
        
        async with self.client:
            # Simulate authenticated state for demo
            self.client.access_token = "demo_token_123"
            self.client.token_expires_at = datetime.now().replace(hour=23, minute=59)
            
            print(f"✅ Simulated authentication: {self.client.is_authenticated()}")
            
            # License validation
            license_result = await self.client.validate_license("demo_hw_fingerprint")
            print(f"✅ License validation attempted: {license_result.success}")
            if not license_result.success:
                print(f"   Error: {license_result.error}")
            
            # License info
            info_result = await self.client.get_license_info()
            print(f"✅ License info request: {info_result.success}")
            if not info_result.success:
                print(f"   Error: {info_result.error}")
        
        print()
    
    async def demo_model_operations(self):
        """Demo: Model management operations"""
        print("🤖 Demo: Model Operations")
        print("-" * 40)
        
        async with self.client:
            # Simulate authenticated state
            self.client.access_token = "demo_token_123"
            self.client.token_expires_at = datetime.now().replace(hour=23, minute=59)
            
            # Get available models
            models_result = await self.client.get_available_models()
            print(f"✅ Available models request: {models_result.success}")
            if not models_result.success:
                print(f"   Error: {models_result.error}")
            
            # Get model metadata
            metadata_result = await self.client.get_model_metadata("llama3_1_8b_fp16")
            print(f"✅ Model metadata request: {metadata_result.success}")
            if not metadata_result.success:
                print(f"   Error: {metadata_result.error}")
            
            # Get download URL
            download_result = await self.client.get_model_download_url("llama3_1_8b_fp16")
            print(f"✅ Download URL request: {download_result.success}")
            if not download_result.success:
                print(f"   Error: {download_result.error}")
        
        print()
    
    async def demo_payment_operations(self):
        """Demo: Payment and subscription operations"""
        print("💳 Demo: Payment Operations")
        print("-" * 40)
        
        async with self.client:
            # Simulate authenticated state
            self.client.access_token = "demo_token_123"
            self.client.token_expires_at = datetime.now().replace(hour=23, minute=59)
            
            # Create payment session
            payment_result = await self.client.create_payment_session("PRO", 12)
            print(f"✅ Payment session creation: {payment_result.success}")
            if not payment_result.success:
                print(f"   Error: {payment_result.error}")
            
            # Get payment history
            history_result = await self.client.get_payment_history()
            print(f"✅ Payment history request: {history_result.success}")
            if not history_result.success:
                print(f"   Error: {history_result.error}")
        
        print()
    
    async def demo_error_handling(self):
        """Demo: Error handling patterns"""
        print("⚠️  Demo: Error Handling")
        print("-" * 40)
        
        # Test with invalid URL
        invalid_client = BackendAPIClient("https://invalid.nonexistent.url")
        
        async with invalid_client:
            result = await invalid_client.test_connection()
            print(f"✅ Invalid URL handled gracefully: {not result.success}")
            print(f"   Error code: {result.error_code}")
            print(f"   Error message: {result.error}")
        
        print()
    
    async def demo_convenience_functions(self):
        """Demo: Convenience functions"""
        print("🛠️  Demo: Convenience Functions")
        print("-" * 40)
        
        # Create API client using convenience function
        client = await create_api_client(self.base_url)
        print(f"✅ Client created via convenience function: {client.base_url}")
        
        # Test connection using convenience function
        is_connected = await test_backend_connection(self.base_url)
        print(f"✅ Connection test via convenience function: {is_connected}")
        
        await client.close_session()
        print()
    
    async def run_all_demos(self):
        """Run all demo scenarios"""
        print("🚀 TikTrue Backend API Client Demo")
        print("=" * 50)
        print(f"Base URL: {self.base_url}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()
        
        demos = [
            self.demo_initialization,
            self.demo_connection_test,
            self.demo_authentication_flow,
            self.demo_license_operations,
            self.demo_model_operations,
            self.demo_payment_operations,
            self.demo_error_handling,
            self.demo_convenience_functions
        ]
        
        for demo in demos:
            try:
                await demo()
            except Exception as e:
                print(f"❌ Demo failed: {e}")
                import traceback
                traceback.print_exc()
                print()
        
        print("✅ All demos completed!")
        print("=" * 50)


async def main():
    """Main demo function"""
    # Use a test URL that won't actually connect
    demo = BackendAPIDemo("https://api.test.tiktrue.com")
    await demo.run_all_demos()


if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("Demo completed successfully!")
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)